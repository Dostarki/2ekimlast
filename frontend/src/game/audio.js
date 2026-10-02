import { CreatureAudio } from './creatureAudio';
import { createCreatureSounds, preloadCreatureSounds } from './creatureSounds';
const TYPES=['ak47','ak117','ak107','m4','shotgun','rocket','minigun','flamethrower','lava','explosion','reload'];
class GameAudio{
  constructor(){this.volume=.35;this.enabled=true;this.buffers={};this.loops=new Map();this.raw={};}
  preload(){
    if(!this.loading)this.loading=Promise.all([...TYPES.map(async type=>{const r=await fetch(`/audio/${type}.wav`);if(!r.ok)throw new Error(`Failed to load audio file: ${type}`);this.raw[type]=await r.arrayBuffer();}),preloadCreatureSounds()]).catch(e=>{this.loading=null;throw e;});
    return this.loading;
  }
  async init(type){
    if(!this.ctx){this.ctx=new(window.AudioContext||window.webkitAudioContext)({latencyHint:'interactive'});this.master=this.ctx.createGain();this.compressor=this.ctx.createDynamicsCompressor();this.compressor.threshold.value=-12;this.compressor.ratio.value=5;this.master.connect(this.compressor);this.compressor.connect(this.ctx.destination);}
    await this.ctx.resume();await this.preload();
    await Promise.all(TYPES.map(async key=>{if(!this.buffers[key])this.buffers[key]=await this.ctx.decodeAudioData(this.raw[key].slice(0));}));
    if(!this.creatures)this.creatures=new CreatureAudio(this,await createCreatureSounds(this.ctx));
    this.sync();
  }
  sync(){if(this.master)this.master.gain.setTargetAtTime(this.enabled?this.volume:0,this.ctx.currentTime,.025);if(!this.enabled||!this.volume)this.creatures?.stop();}
  enemies(state){this.creatures?.update(state);}
  stopEnemies(){this.creatures?.stop();}
  play(type,{gain=1,rate=1,pan=0}={}){
    if(!this.ctx||!this.buffers[type]||!this.enabled||!this.volume)return;
    this.sync();const source=this.ctx.createBufferSource(),level=this.ctx.createGain(),stereo=this.ctx.createStereoPanner();source.buffer=this.buffers[type];source.playbackRate.value=rate;level.gain.value=gain;stereo.pan.value=Math.max(-1,Math.min(1,pan));source.connect(level);level.connect(stereo);stereo.connect(this.master);source.start();source.onended=()=>{source.disconnect();level.disconnect();stereo.disconnect();};return source;
  }
  shot(type='ak47',remote=false,distance=0,pan=0){
    // Existing licensed firearm sample, pitched for the pistol; not a Glock recording.
    if(type==='glock18'){this.play('m4',{gain:remote?Math.max(.04,1/(1+distance*.13)):.60,rate:1.22,pan});return;}
    if(!this.ctx||!this.buffers[type])return;
    if(!remote&&['minigun','flamethrower'].includes(type)){
      if(!this.loops.has(type)){this.sync();const s=this.ctx.createBufferSource(),g=this.ctx.createGain();s.buffer=this.buffers[type];s.loop=true;s.loopStart=.04;s.loopEnd=Math.max(.08,s.buffer.duration-.08);g.gain.value=type==='minigun'?.8:1.25;s.connect(g);g.connect(this.master);s.start();this.loops.set(type,{s,g});}
      return;
    }
    this.play(type,{gain:remote?Math.max(.04,1/(1+distance*.13)):.85,rate:1+(Math.random()-.5)*.025,pan});
  }
  stopAutomatic(){
    if(!this.ctx)return;this.loops.forEach(({s,g})=>{g.gain.setTargetAtTime(0,this.ctx.currentTime,.025);s.stop(this.ctx.currentTime+.12);s.onended=()=>{s.disconnect();g.disconnect();};});this.loops.clear();
  }
  explosion(distance=0){this.play('explosion',{gain:1/(1+distance*.08)});}
  reload(){this.play('reload',{gain:.6});}
  supply(){if(!this.ctx||!this.enabled)return;const o=this.ctx.createOscillator(),g=this.ctx.createGain(),t=this.ctx.currentTime;o.frequency.setValueAtTime(600,t);o.frequency.setValueAtTime(900,t+.08);g.gain.setValueAtTime(.1,t);g.gain.exponentialRampToValueAtTime(.001,t+.24);o.connect(g);g.connect(this.master);o.start();o.stop(t+.25);}
}
export const audio=new GameAudio();