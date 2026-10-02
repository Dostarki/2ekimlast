import * as THREE from 'three';
import { FlameStreams } from './flameStreams';

export class SceneEffects{
  constructor(scene){this.scene=scene;this.particles=[];this.projectiles=new Map();this.fires=new Map();this.sphere=new THREE.IcosahedronGeometry(1,0);this.pool=[];this.streams=new FlameStreams(scene);}
  particle(x,y,z,color,size,life,velocity){
    if(this.particles.length>=48)return;
    let mesh=this.pool.pop();if(!mesh)mesh=new THREE.Mesh(this.sphere,new THREE.MeshBasicMaterial({transparent:true,depthWrite:false}));
    mesh.material.color.set(color);mesh.material.opacity=.9;mesh.position.set(x,y,z);mesh.scale.setScalar(size);mesh.visible=true;this.scene.add(mesh);this.particles.push({mesh,life,max:life,size,velocity:velocity||new THREE.Vector3(0,.8,0)});
  }
  shot(e){
    const dx=e.tx-e.x,dz=e.tz-e.z,len=Math.max(.01,Math.hypot(dx,dz)),nx=dx/len,nz=dz/len;
    if(e.kind==='flame'){
      this.streams.emit(e);
      for(let i=0;i<9;i++){const f=(i+.5)/9;this.particle(e.x+dx*f,1.0+Math.random()*.5,e.z+dz*f,i%3?'#ff8b27':'#ffd976',.15+f*.40,.24+Math.random()*.16,new THREE.Vector3(nx*4,1.5,nz*4));}
    }else{
      this.particle(e.x+nx*1.6,1.4,e.z+nz*1.6,e.kind==='lava'?'#ee571a':'#ffe2a3',e.kind==='rocket'?.38:.20,.07,new THREE.Vector3());
      if(e.kind==='bullet'||!e.kind){const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(e.x+nx*1.5,1.36,e.z+nz*1.5),new THREE.Vector3(e.tx,1.1,e.tz)]),new THREE.LineBasicMaterial({color:'#f6dca0',transparent:true,opacity:.65}));this.scene.add(line);this.particles.push({mesh:line,life:.065,max:.065,line:true});}
    }
  }
  explosion(e){for(let i=0;i<18;i++){const a=Math.random()*Math.PI*2,r=Math.random()*e.r*.65;this.particle(e.x+Math.sin(a)*r,.5+Math.random()*1.5,e.z+Math.cos(a)*r,i%2?'#f08931':'#eab76e',.4+Math.random()*.8,.45+Math.random()*.35,new THREE.Vector3(Math.sin(a)*2,1.8,Math.cos(a)*2));}}
  sync(state){
    const wanted=new Set();(state.projectiles||[]).forEach(p=>{wanted.add(p.id);let m=this.projectiles.get(p.id);if(!m){m=new THREE.Mesh(p.kind==='lava'?new THREE.SphereGeometry(.28,10,8):new THREE.CapsuleGeometry(.10,.9,3,8),new THREE.MeshBasicMaterial({color:p.kind==='lava'?'#ff7229':'#dcaf65'}));m.position.set(p.x,1.2,p.z);this.scene.add(m);this.projectiles.set(p.id,m);}m.userData.target=p;});
    this.projectiles.forEach((m,id)=>{if(!wanted.has(id)){this.scene.remove(m);m.geometry.dispose();m.material.dispose();this.projectiles.delete(id);}});
    const active=new Set();(state.fires||[]).forEach(f=>{active.add(f.id);let m=this.fires.get(f.id);if(!m){m=new THREE.Mesh(new THREE.CircleGeometry(f.r,28),new THREE.MeshBasicMaterial({color:'#d44c16',transparent:true,opacity:.65,depthWrite:false}));m.rotation.x=-Math.PI/2;m.position.set(f.x,.13,f.z);this.scene.add(m);this.fires.set(f.id,m);}m.userData.fire=f;});
    this.fires.forEach((m,id)=>{if(!active.has(id)){this.scene.remove(m);m.geometry.dispose();m.material.dispose();this.fires.delete(id);}});
  }
  update(dt,time){
    this.streams.update(time);
    for(let i=this.particles.length-1;i>=0;i--){const p=this.particles[i];p.life-=dt;if(p.life<=0){this.scene.remove(p.mesh);if(p.line){p.mesh.geometry.dispose();p.mesh.material.dispose();}else this.pool.push(p.mesh);this.particles.splice(i,1);continue;}p.mesh.material.opacity=p.life/p.max*.85;if(!p.line){p.mesh.position.addScaledVector(p.velocity,dt);p.mesh.scale.setScalar(p.size*(1+(1-p.life/p.max)*.6));}}
    this.projectiles.forEach(m=>{const p=m.userData.target,y=p.kind==='lava'?.4+Math.sin((1-p.remaining/p.total)*Math.PI)*4:1.2;m.position.lerp(new THREE.Vector3(p.x,y,p.z),1-Math.exp(-dt*24));if(p.kind==='rocket'){m.rotation.set(Math.PI/2,0,-Math.atan2(p.dx,p.dz));}});
    this.fires.forEach(m=>{const f=m.userData.fire;m.material.opacity=.5+Math.sin(time*9)*.1;if(Math.random()<dt*18){const a=Math.random()*6.28,r=Math.random()*f.r;this.particle(f.x+Math.cos(a)*r,.3,f.z+Math.sin(a)*r,'#ffb43f',.20,.5,new THREE.Vector3(0,2,0));}});
  }
  clear(){this.streams.clear();this.particles.forEach(p=>{this.scene.remove(p.mesh);if(p.line){p.mesh.geometry.dispose();p.mesh.material.dispose();}else this.pool.push(p.mesh);});this.particles=[];this.sync({projectiles:[],fires:[]});}
}