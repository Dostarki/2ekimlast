export class CreatureAudio {
  constructor(audio, buffers) {
    this.audio=audio; this.buffers=buffers; this.voices=new Set(); this.idleAt=new Map(); this.buzz=null;
    this.metrics={ played:0, last:'', swarm:false };
  }
  spatial(x,z,me,range=65) {
    const dx=x-me.x,dz=z-me.z,distance=Math.hypot(dx,dz);
    return { gain:distance>=range ? 0 : Math.pow(1-distance/range,1.8)*.7, pan:Math.max(-1,Math.min(1,(dx-dz)/35)) };
  }
  play(kind,action,x,z,me) {
    const a=this.audio, spatial=this.spatial(x,z,me,action === 'idle' ? 32 : 70);
    if (!a.enabled || !a.volume || spatial.gain<.008 || this.voices.size>=8) return;
    const buffer=this.buffers[`${kind}-${action}`]; if(!buffer)return;
    const source=a.ctx.createBufferSource(),gain=a.ctx.createGain(),pan=a.ctx.createStereoPanner();
    source.buffer=buffer; source.playbackRate.value=.93+Math.random()*.14; gain.gain.value=spatial.gain; pan.pan.value=spatial.pan;
    source.connect(gain);gain.connect(pan);pan.connect(a.master);this.voices.add(source);
    source.onended=()=>{this.voices.delete(source);source.disconnect();gain.disconnect();pan.disconnect();};source.start();
    this.metrics.played++;this.metrics.last=`${kind}-${action}`;
  }
  update(state) {
    const a=this.audio,me=state.me;
    if(!a.enabled||!a.volume||!me||me.hp<=0){this.stop();return;}
    const now=a.ctx.currentTime;
    for(const event of state.events||[]) if(event.type==='enemy_sound')this.play(event.enemy_type,event.action,event.x,event.z,me);
    const nearby=(state.zombies||[]).filter(z=>z.hp>0).sort((a,b)=>Math.hypot(a.x-me.x,a.z-me.z)-Math.hypot(b.x-me.x,b.z-me.z));
    const ids=new Set(nearby.map(z=>z.id)); this.idleAt.forEach((_,id)=>{if(!ids.has(id))this.idleAt.delete(id);});
    for(const enemy of nearby.slice(0,5)) {
      if(!this.idleAt.has(enemy.id))this.idleAt.set(enemy.id,now+1+Math.random()*3);
      if(now>this.idleAt.get(enemy.id)){this.play(enemy.enemy_type,'idle',enemy.x,enemy.z,me);this.idleAt.set(enemy.id,now+4+Math.random()*5);}
    }
    const swarm=(state.swarms||[]).filter(s=>ids.has(s.owner)).sort((a,b)=>Math.hypot(a.x-me.x,a.z-me.z)-Math.hypot(b.x-me.x,b.z-me.z))[0];
    const spatial=swarm ? this.spatial(swarm.x,swarm.z,me,26) : {gain:0,pan:0};
    if(spatial.gain>.01){
      if(!this.buzz){const source=a.ctx.createBufferSource(),gain=a.ctx.createGain(),pan=a.ctx.createStereoPanner();source.buffer=this.buffers.swarm;source.loop=true;source.connect(gain);gain.connect(pan);pan.connect(a.master);source.start();this.buzz={source,gain,pan};}
      this.buzz.gain.gain.setTargetAtTime(spatial.gain*.55,now,.08);this.buzz.pan.pan.setTargetAtTime(spatial.pan,now,.08);
    } else this.stopBuzz();
    this.metrics.swarm=!!this.buzz;
  }
  stopBuzz(){if(!this.buzz)return;const {source,gain,pan}=this.buzz;source.stop();source.disconnect();gain.disconnect();pan.disconnect();this.buzz=null;this.metrics.swarm=false;}
  stop(){this.stopBuzz();this.voices.forEach(s=>{try{s.stop();}catch{}});this.voices.clear();this.idleAt.clear();}
}