import * as THREE from 'three';
import {box,cylinder,material} from './models';
import {bakeMeshes} from './batching';

function batch(group){
  const meshes=group.children.filter(o=>o.isMesh),baked=bakeMeshes(meshes);meshes.forEach(m=>{group.remove(m);m.geometry.dispose();});baked.forEach(m=>group.add(m));return group;
}
function sign(text){
  const c=document.createElement('canvas');c.width=768;c.height=96;const ctx=c.getContext('2d');ctx.fillStyle='#293b32';ctx.fillRect(0,0,768,96);ctx.fillStyle='#d5dabb';ctx.font='600 44px sans-serif';ctx.textAlign='center';ctx.fillText(text,384,62);
  const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c),transparent:true,depthWrite:false}));sprite.scale.set(10,1.25,1);return sprite;
}
export function createInterior(h){
  const base=new THREE.Group(),cover=new THREE.Group(),{x,z,w,d}=h;
  box(base,x,.05,z,w,.09,d,h.kind==='home'?'#898071':'#9eaaa0');
  for(let i=-w/2+1;i<w/2;i+=2)box(base,x+i,.102,z,.025,.006,d,'#758178');
  for(let i=-d/2+1;i<d/2;i+=2)box(base,x,.103,z+i,w,.006,.025,'#758178');
  for(const wall of h.walls){box(base,wall.x,.33,wall.z,wall.w,.66,wall.d,'#859584');box(cover,wall.x,(h.h+.66)/2,wall.z,wall.w,h.h-.66,wall.d,h.kind==='gas'?'#c1c5b5':'#acb4a3');}
  const roofY=h.h+.15;
  box(cover,x,roofY,z,w+.8,.35,d+.8,h.kind==='gas'?'#6b8d82':h.kind==='hotel'?'#505e59':'#647365');
  for(const side of [-1,1])box(cover,x+side*w/2,roofY+.3,z,.25,.55,d+.7,'#aeb7a0');
  box(cover,x,roofY+.3,z+d/2,w+.7,.55,.25,'#aeb7a0');
  const label=sign(h.kind==='gas'?'WESTFALL FUEL':h.kind==='hotel'?'WESTFALL HOTEL':'WESTFALL HOME');label.position.set(x,h.h+1.8,z-d/2);cover.add(label);
  // Open hinged door: real navigable 3.2 m opening, no invisible building box.
  box(base,x-1.65,1.45,z-d/2+1.3,.12,2.9,2.6,'#526759');
  box(cover,x,h.h-.2,z-d/2,3.2,.4,.5,'#778d7d');
  box(base,x,.035,z-d/2-3,3.2,.07,6,'#939e8c');
  for(const f of h.furniture){
    if(f.kind==='counter'){box(base,f.x,.62,f.z,f.w,1.24,f.d,'#5b6f61');box(base,f.x,1.3,f.z,f.w+.16,.14,f.d+.12,'#d1cbb6');box(base,f.x+.6,1.54,f.z,.58,.4,.4,'#263b34');}
    if(f.kind==='sofa'){box(base,f.x,.45,f.z,f.w,.75,f.d,'#677c67');box(base,f.x,.94,f.z+.48,f.w,.64,.30,'#536f5a');for(const s of[-1,1])box(base,f.x+s*(f.w/2-.18),.74,f.z,.35,.65,f.d,'#536f5a');}
    if(f.kind==='bed'){box(base,f.x,.30,f.z,f.w,.60,f.d,'#576659');box(base,f.x,.69,f.z,f.w-.10,.25,f.d-.1,'#c4c3ae');box(base,f.x,.85,f.z-.95,f.w-.3,.15,.63,'#e1dfcc');box(base,f.x,.85,f.z+.4,f.w-.16,.13,1.9,'#688776');}
    if(f.kind==='shelf'){box(base,f.x,.95,f.z,f.w,1.9,f.d,'#657262');for(let j=0;j<3;j++){box(base,f.x,1.9+j*.02,f.z,1.18,.10,f.d+.1,'#b0ae8b');for(let k=0;k<6;k++)box(base,f.x,1.99+j*.12,f.z-f.d/2+.4+k*.55,.45,.18,.27,['#9d7661','#8e986c','#c5b274'][j]);}}
  }
  if(h.kind==='gas'){
    const pumpZ=z-d/2-6;
    for(const side of[-1,1]){const px=x+side*5.5;box(base,px,.68,pumpZ,1.0,1.36,.8,'#94a79c');box(base,px,1.54,pumpZ,1.1,.65,.86,'#c8d0bf');box(base,px,1.56,pumpZ-.44,.6,.29,.02,'#233932');cylinder(base,px+.73,.75,pumpZ,.07,1.2,'#23382e');}
    box(base,x,3.1,pumpZ,w*.84,.28,4,'#648d7d');for(const side of[-1,1])box(base,x+side*w*.36,1.5,pumpZ,.15,3,.15,'#adb7a2');
  }
  const group=new THREE.Group();group.add(batch(base));group.add(batch(cover));group.userData.building=h;group.userData.cover=cover;return group;
}