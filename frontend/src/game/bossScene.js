import * as THREE from 'three';
import { createBoss, animateBoss, disposeBoss } from './bossModels';

const UP=new THREE.Vector3(0,1,0);
export class BossScene{
  constructor(scene,fx){this.scene=scene;this.fx=fx;this.models=new Map();this.warnings=new Map();this.projectiles=new Map();this.zones=new Map();this.beams=[];this.ringGeometry=new THREE.RingGeometry(.88,1,48);this.floorGeometry=new THREE.CircleGeometry(1,48);this.sphere=new THREE.IcosahedronGeometry(.45,1);}
  remove(map,id){const m=map.get(id);if(m){m.removeFromParent();m.material?.dispose();map.delete(id);}}
  sync(state){
    const wanted=new Set();
    for(const data of state.bosses||[]){
      if(!data.alive||Math.hypot(data.x-state.me.x,data.z-state.me.z)>145)continue;
      wanted.add(data.id);let g=this.models.get(data.id);
      if(!g){g=createBoss(data);g.position.set(data.x,data.y||0,data.z);this.scene.add(g);this.models.set(data.id,g);}g.userData.target=data;
      if(data.telegraph){let ring=this.warnings.get(data.id);if(!ring){ring=new THREE.Mesh(this.ringGeometry,new THREE.MeshBasicMaterial({color:'#ff6753',transparent:true,opacity:.75,side:THREE.DoubleSide,depthWrite:false}));ring.rotation.x=-Math.PI/2;this.scene.add(ring);this.warnings.set(data.id,ring);}ring.position.set(data.telegraph.x,.15,data.telegraph.z);ring.scale.setScalar(data.telegraph.r);}
      else this.remove(this.warnings,data.id);
    }
    this.models.forEach((g,id)=>{if(!wanted.has(id)){disposeBoss(g);this.models.delete(id);this.remove(this.warnings,id);}});
    for(const [entries,map,zone] of [[state.boss_projectiles||[],this.projectiles,false],[state.boss_zones||[],this.zones,true]]){
      const ids=new Set(entries.map(e=>e.id));map.forEach((_,id)=>{if(!ids.has(id))this.remove(map,id);});
      entries.forEach(e=>{let m=map.get(e.id);if(!m){m=new THREE.Mesh(zone?this.floorGeometry:this.sphere,new THREE.MeshBasicMaterial({color:zone?'#fb7234':e.kind==='web'?'#f0719b':'#ffcb73',transparent:true,opacity:zone?.72:1,side:THREE.DoubleSide}));this.scene.add(m);map.set(e.id,m);}m.userData.target=e;if(zone){m.rotation.x=-Math.PI/2;m.position.set(e.x,.12,e.z);m.scale.setScalar(e.r);}else m.position.set(e.x,e.y,e.z);});
    }
  }
  event(e){
    if(e.type==='boss_impact'){this.fx.explosion({x:e.x,z:e.z,r:e.r,kind:e.kind==='lava'?'lava':'boss'});}
    if(e.type==='boss_beam'){
      const a=new THREE.Vector3(e.x,e.height,e.z),b=new THREE.Vector3(e.tx,.85,e.tz),delta=b.clone().sub(a);
      const mesh=new THREE.Mesh(new THREE.CylinderGeometry(e.kind==='tail'?.16:.18,e.kind==='tail'?.16:.40,delta.length(),8),new THREE.MeshBasicMaterial({color:e.kind==='tail'?'#d0dfb4':'#ff5e47',transparent:true,opacity:.92}));mesh.position.copy(a).add(b).multiplyScalar(.5);mesh.quaternion.setFromUnitVectors(UP,delta.normalize());this.scene.add(mesh);this.beams.push({mesh,until:performance.now()+360});
    }
  }
  update(dt,time){
    this.models.forEach(g=>{const e=g.userData.target;g.position.x+=(e.x-g.position.x)*(1-Math.exp(-dt*18));g.position.z+=(e.z-g.position.z)*(1-Math.exp(-dt*18));animateBoss(g,e,dt,time);});
    this.warnings.forEach(m=>{m.material.opacity=.45+Math.sin(time*12)*.25;});
    this.zones.forEach(m=>{m.material.opacity=.55+Math.sin(time*7)*.15;const e=m.userData.target;if(Math.random()<.3)this.fx.particle(e.x+(Math.random()-.5)*e.r,0,e.z+(Math.random()-.5)*e.r,'#ff963e',.28,.7,0,2,0);});
    for(let i=this.beams.length-1;i>=0;i--)if(performance.now()>this.beams[i].until){const m=this.beams[i].mesh;m.removeFromParent();m.geometry.dispose();m.material.dispose();this.beams.splice(i,1);}
  }
  clear(){this.models.forEach(disposeBoss);this.models.clear();[this.warnings,this.projectiles,this.zones].forEach(map=>{[...map.keys()].forEach(id=>this.remove(map,id));});this.beams.forEach(({mesh})=>{mesh.removeFromParent();mesh.geometry.dispose();mesh.material.dispose();});this.beams=[];}
  dispose(){this.clear();this.ringGeometry.dispose();this.floorGeometry.dispose();this.sphere.dispose();}
}