import * as THREE from 'three';
import { box, rounded, limb, material, mergeBody, disposeHuman } from './characterParts';

const bossColors = { hansel:'#f3ae52', symbiote:'#eb6c80', xenomorph:'#94d6bf', ash_titan:'#f88b5c' };
function sphere(g,x,y,z,w,h,d,color,detail=1){const m=new THREE.Mesh(new THREE.IcosahedronGeometry(1,detail),material(color,.55));m.position.set(x,y,z);m.scale.set(w,h,d);m.castShadow=true;g.add(m);return m;}
function tube(g,points,radius,color){const curve=new THREE.CatmullRomCurve3(points.map(v=>new THREE.Vector3(...v)));const m=new THREE.Mesh(new THREE.TubeGeometry(curve,20,radius,6,false),material(color,.5));g.add(m);return m;}
function fang(g,x,y,z,h,color,angle=0){const m=new THREE.Mesh(new THREE.ConeGeometry(h*.2,h,6),material(color));m.position.set(x,y,z);m.rotation.x=angle;g.add(m);return m;}
function robot(g){
  const gray='#737d7a',dark='#252e2d',orange='#b6762d';
  rounded(g,0,1.51,0,1.21,.94,.70,gray,.13);rounded(g,0,1.57,.36,.82,.65,.13,dark,.07);
  for(let i=0;i<7;i++)box(g,-.30+i*.10,1.56,.45,.045,.49,.035,'#4b5551');
  rounded(g,0,2.23,0,.67,.61,.61,gray,.14);rounded(g,0,2.22,.31,.46,.15,.05,'#151f1b');
  box(g,0,2.24,.345,.36,.055,.025,'#ffc766');
  for(const s of [-1,1]){box(g,s*.31,2.25,.13,.09,.36,.48,orange);rounded(g,s*.58,1.80,0,.31,.26,.72,orange);}
  const arms=[],legs=[];
  for(const s of [-1,1]){
    const arm=new THREE.Group();arm.position.set(s*.88,1.78,0);g.add(arm);
    rounded(arm,0,-.21,0,.46,.58,.49,gray,.12);rounded(arm,0,-.64,.12,.63,.48,.70,dark,.12);
    for(let i=0;i<3;i++)rounded(arm,(i-1)*.17,-.63,.49,.14,.29,.06,orange,.015);mergeBody(arm);arms.push(arm);
    const leg=new THREE.Group();leg.position.set(s*.34,1.03,0);g.add(leg);
    rounded(leg,0,-.29,0,.43,.59,.47,gray,.07);rounded(leg,0,-.63,.06,.42,.36,.50,dark);rounded(leg,0,-.90,.15,.55,.24,.73,gray);mergeBody(leg);legs.push(leg);
    rounded(g,s*.78,1.98,-.26,.37,.33,.43,dark);
    for(let i=0;i<3;i++)sphere(g,s*.78,1.90+i*.085,-.02,.047,.047,.035,'#c38649');
  }
  return {arms,legs};
}
function organic(g,kind){
  const sym=kind==='symbiote',ash=kind==='ash_titan',base=ash?'#656a62':sym?'#23282a':'#303b3a';
  sphere(g,0,1.42,0,ash?.69:sym?.56:.35,.61,.32,base,ash?0:2);
  sphere(g,0,.98,0,.31,.26,.27,base);
  if(ash){
    sphere(g,0,1.58,.13,.48,.55,.28,'#e37930');
    for(let i=0;i<9;i++)sphere(g,(i%3-1)*.36,1.10+Math.floor(i/3)*.30,.25,.27,.24,.18,i%2?'#555b54':'#858a7d',0);
    sphere(g,0,2.25,0,.30,.36,.28,'#74796a',0);box(g,0,2.31,.27,.36,.035,.04,'#ffc26c');
    for(const s of [-1,1])fang(g,s*.23,2.64,0,.50,'#696f62',s*.3);
  }else if(sym){
    for(const s of [-1,1])sphere(g,s*.25,1.70,.21,.29,.26,.15,'#742d3b',2);
    sphere(g,0,2.26,.03,.27,.34,.26,base,2);rounded(g,0,2.14,.28,.41,.16,.08,'#0e1415');
    for(const s of [-1,1]){const eye=rounded(g,s*.13,2.37,.245,.17,.095,.025,'#dfddd2');eye.rotation.z=-s*.3;}
    for(let i=0;i<8;i++)fang(g,-.175+i*.05,2.16,.33,.073,'#dfd3b1',Math.PI);
    for(let i=0;i<5;i++)tube(g,[[0,1.01+i*.13,.28],[.17,1.04+i*.13,.32],[.32,1.15+i*.13,.24]],.022,'#922f42');
    for(const s of [-1,1])for(let i=0;i<3;i++)tube(g,[[s*.37,1.7,-.15],[s*(.8+i*.13),1.9+i*.15,-.35],[s*(1.2+i*.1),2.30,-.35],[s*(1.12+i*.1),2.52,-.10]],.035,'#873342');
  }else{
    const dome=limb(g,0,2.11,-.05,.23,1.1,'#253031',1.05);dome.rotation.x=Math.PI/2;
    rounded(g,0,1.99,.41,.31,.15,.20,'#11191a');for(let i=0;i<7;i++)fang(g,-.12+i*.04,1.96,.53,.065,'#d6d8c7',Math.PI);
    for(let i=0;i<7;i++){const rib=rounded(g,0,1.18+i*.075,.25,.54-i*.026,.028,.048,'#69746b');rib.rotation.z=Math.sin(i)*.06;}
    for(const s of [-1,1])for(let i=0;i<3;i++)tube(g,[[s*.20,1.40+i*.14,-.20],[s*.30,1.70+i*.15,-.55],[s*.34,1.94+i*.14,-.61]],.065,'#414f4b');
    const tail=new THREE.Group();g.add(tail);
    const pts=[[0,.96,-.15],[.15,.67,-.8],[.57,.28,-1.8],[1.2,.40,-2.15],[1.8,.90,-1.8],[1.65,1.37,-1.1]];
    tube(tail,pts,.077,'#46514a');for(let i=0;i<12;i++)sphere(tail,.15+i*.10,.60-Math.sin(i*.22)*.27,-.8-i*.10,.11,.095,.10,'#667162',0);
    fang(tail,1.65,1.52,-1.1,.49,'#879383',.15);g.userData.tail=tail;
  }
  const arms=[],legs=[];
  for(const s of [-1,1]){
    const arm=new THREE.Group();arm.position.set(s*(ash?.84:sym?.65:.43),1.79,0);g.add(arm);
    sphere(arm,0,-.20,0,ash?.29:.20,.38,.23,base,ash?0:1);sphere(arm,s*.06,-.66,.05,ash?.30:.16,.30,.22,ash?'#747a6e':base,ash?0:1);
    if(ash){box(arm,0,-.61,.25,.22,.07,.04,'#ffb85e');sphere(arm,0,-.89,.08,.29,.23,.27,base,0);}else for(let i=0;i<4;i++)fang(arm,(i-1.5)*.072,-.98,.09,.25,sym?'#ab6570':'#b4bbaa',Math.PI);
    mergeBody(arm);arms.push(arm);
    const leg=new THREE.Group();leg.position.set(s*.28,1,0);g.add(leg);
    limb(leg,0,-.25,0,ash?.23:.16,.55,base);limb(leg,0,-.66,.01,ash?.21:.12,.39,base);rounded(leg,0,-.92,.13,ash?.53:.31,.20,.51,base);mergeBody(leg);legs.push(leg);
  }
  return {arms,legs};
}
export function createBoss(data){
  const root=new THREE.Group(),body=new THREE.Group();root.add(body);
  const rig=data.boss_type==='hansel'?robot(body):organic(body,data.boss_type);mergeBody(body);
  const scale=data.height/(data.boss_type==='ash_titan'?2.9:data.boss_type==='xenomorph'?2.4:2.6);body.scale.setScalar(scale);
  const ring=new THREE.Mesh(new THREE.RingGeometry(data.radius+.2,data.radius+.33,48),new THREE.MeshBasicMaterial({color:bossColors[data.boss_type],transparent:true,opacity:.65,side:THREE.DoubleSide,depthWrite:false}));ring.rotation.x=-Math.PI/2;ring.position.y=.05;root.add(ring);
  const canvas=document.createElement('canvas');canvas.width=512;canvas.height=96;const ctx=canvas.getContext('2d');ctx.fillStyle='rgba(14,22,18,.82)';ctx.fillRect(0,0,512,96);ctx.fillStyle=bossColors[data.boss_type];ctx.font='bold 42px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(data.name,256,48);
  const map=new THREE.CanvasTexture(canvas);const label=new THREE.Sprite(new THREE.SpriteMaterial({map,depthTest:false}));label.position.y=data.height+1.5;label.scale.set(9,1.7,1);root.add(label);
  root.userData={body,rig,label,phase:0,baseScale:scale,kind:data.boss_type,tail:body.userData.tail};return root;
}
export function animateBoss(g,data,dt,time){
  const u=g.userData,moving=data.action==='chase',liquid=data.action==='liquid',attack=['slash','claw','bite','slam','quake'].includes(data.action);
  u.phase+=dt*(moving?5:1);u.body.rotation.y=data.angle;
  u.rig.legs.forEach((leg,i)=>{leg.rotation.x=Math.sin(u.phase+i*Math.PI)*(moving?.35:0);});
  u.rig.arms.forEach((arm,i)=>{arm.rotation.x=attack?-1.05:data.action.startsWith('windup')?-.3:Math.sin(u.phase+i*Math.PI)*(moving?.25:.03);});
  u.body.scale.set(u.baseScale*(liquid?1.8:1),u.baseScale*(liquid?.07:1),u.baseScale*(liquid?1.8:1));
  if(u.tail)u.tail.rotation.y=data.action==='tail'?-1.1:Math.sin(time*1.7)*.12;
  u.label.visible=!liquid;g.position.y=data.y||0;
}
export function disposeBoss(g){const label=g.userData.label;label.removeFromParent();label.material.map.dispose();label.material.dispose();disposeHuman(g);}