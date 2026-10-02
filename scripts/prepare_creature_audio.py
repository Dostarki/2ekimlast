"""Edit licensed voice/animal/insect recordings into short game effects; not a test."""
from pathlib import Path
import subprocess
import wave
import numpy as np

ROOT = Path('/root/deadzone-creature-audio')
OUT = Path('/app/frontend/public/audio/creatures')
OUT.mkdir(parents=True, exist_ok=True)
RATE = 22050


def decode(path):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '1', '-ar', str(RATE), 'pipe:1'])
    return np.frombuffer(raw, dtype=np.float32).copy()


def clip(samples, start, end, duration=1.4, pitch=1):
    region = samples[int(start*RATE):int(end*RATE)]
    if not len(region):
        raise ValueError('Selected recording segment is empty')
    size = min(len(region), int(duration*RATE*pitch))
    starts = list(range(0, max(1, len(region)-size+1), 1102))
    offset = max(starts, key=lambda p: float(np.mean(region[p:p+size]**2)))
    result = region[offset:offset+size]
    if pitch != 1:
        result = np.interp(np.arange(0,len(result),pitch),np.arange(len(result)),result).astype(np.float32)
    return result


def mix(a, b, gain=.35):
    result = a.copy()
    n = min(len(a),len(b)); result[:n] += b[:n]*gain
    return result


def save(name, samples, loop=False):
    samples = samples.copy(); samples -= np.mean(samples)
    peak = float(np.max(np.abs(samples)))
    if peak < .0001:
        raise ValueError(f'Silent recording: {name}')
    samples = np.tanh(samples/peak*1.6)*.78
    fade = min(900,len(samples)//8)
    if loop:
        # Equal-power crossfade makes a seamless recorded insect loop.
        blend = np.linspace(0,1,fade)
        samples[:fade] = samples[:fade]*blend+samples[-fade:]*(1-blend)
        samples = samples[:-fade]
    else:
        samples[:120] *= np.linspace(0,1,120); samples[-fade:] *= np.linspace(1,0,fade)
    with wave.open(str(OUT/(name+'.wav')),'wb') as file:
        file.setnchannels(1); file.setsampwidth(2); file.setframerate(RATE)
        file.writeframes((samples*32767).astype(np.int16).tobytes())
    print(name, round(len(samples)/RATE,2), 'seconds')


monster, death, dog, cry, bees = [decode(ROOT/(name+'.mp3')) for name in ['monster','death','dog','dog-cry','bees']]
torch = decode(OUT.parent/'flamethrower.wav')
regions = {'idle': (1,4,1.8), 'aggro': (10,14,1.5), 'attack': (14,18,.85), 'hurt': (88,92,.50)}
for action in ['idle','aggro','attack','hurt','death']:
    region = regions.get(action,(0,1.8,1.5)); source = death if action == 'death' else monster
    normal = clip(source,*region)
    save('normal-'+action,normal)
    firevoice = clip(source,*region,pitch=.91)
    save('immolator-'+action, mix(firevoice,clip(torch,0,2,len(firevoice)/RATE),.65))
    raspy = clip(death,0,1.8,1.3,1.15) if action == 'death' else clip(monster,39,43,region[2],1.12)
    save('hive-'+action,mix(raspy,clip(bees,2,10,len(raspy)/RATE),.24))
    armored = clip(death,0,1.8,1.7,.77) if action == 'death' else clip(monster,73 if action in ('idle','aggro') else 104,79 if action in ('idle','aggro') else 111,region[2],.80)
    if action in ('attack','hurt'):
        armored = mix(armored,clip(monster,114,117,.45),.5)
    save('armored-'+action,armored)
    dogsource = cry if action == 'death' else dog
    start,end = (0,13.5) if action == 'death' else (0,3.7) if action in ('idle','hurt') else (3.7,7.5)
    bark = clip(dogsource,start,end,1.25 if action != 'hurt' else .65,.96 if action in ('aggro','attack') else 1)
    save('hellhound-'+action,bark)
swarm = clip(bees,1,10,2.8)
swarm = mix(swarm,np.roll(swarm,5200),.42)
save('swarm',swarm,loop=True)